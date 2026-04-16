from __future__ import annotations

from django.db.models import QuerySet

from apps.pricing.models import ProductPrice, SupplierOffer


def get_operational_supplier_offers_queryset() -> QuerySet[SupplierOffer]:
    return SupplierOffer.objects.select_related(
        "supplier",
        "product",
        "product__brand",
        "product__category",
    ).order_by("-updated_at")


def get_operational_product_prices_queryset() -> QuerySet[ProductPrice]:
    return ProductPrice.objects.select_related(
        "product",
        "product__brand",
        "product__category",
        "policy",
    ).order_by("-updated_at")


def apply_operational_supplier_offer_filters(queryset: QuerySet[SupplierOffer], *, params) -> QuerySet[SupplierOffer]:
    supplier_code = params.get("supplier", "").strip()
    available = params.get("is_available", "").strip().lower()

    if supplier_code:
        queryset = queryset.filter(supplier__code=supplier_code)

    if available in {"true", "1", "yes"}:
        queryset = queryset.filter(is_available=True)
    elif available in {"false", "0", "no"}:
        queryset = queryset.filter(is_available=False)

    return queryset


def apply_operational_product_price_filters(queryset: QuerySet[ProductPrice], *, params) -> QuerySet[ProductPrice]:
    min_price = params.get("min_final_price", "").strip()
    max_price = params.get("max_final_price", "").strip()

    if min_price:
        try:
            queryset = queryset.filter(final_price__gte=min_price)
        except (ValueError, TypeError):
            pass

    if max_price:
        try:
            queryset = queryset.filter(final_price__lte=max_price)
        except (ValueError, TypeError):
            pass

    return queryset
