from __future__ import annotations

from django.db.models import QuerySet

from apps.supplier_imports.models import SupplierRawOffer


def get_supplier_raw_offers_publish_queryset(*, supplier_code: str) -> QuerySet[SupplierRawOffer]:
    return (
        SupplierRawOffer.objects.select_related(
            "supplier",
            "mapped_category",
            "matched_product",
            "matched_product__brand",
            "matched_product__category",
        )
        .filter(supplier__code=supplier_code)
        .order_by("-updated_at", "-created_at")
    )

