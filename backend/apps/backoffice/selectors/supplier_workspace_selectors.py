from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, ImportSource
from apps.supplier_imports.selectors import ensure_default_import_sources


SUPPORTED_SUPPLIER_CODES = ("utr", "gpl")


def get_supplier_workspace_sources_queryset() -> QuerySet[ImportSource]:
    ensure_default_import_sources()
    return (
        ImportSource.objects.filter(code__in=SUPPORTED_SUPPLIER_CODES)
        .select_related("supplier")
        .order_by("name")
    )


def get_supplier_source_by_code(*, supplier_code: str) -> ImportSource:
    ensure_default_import_sources()
    return (
        ImportSource.objects.select_related("supplier")
        .filter(code__in=SUPPORTED_SUPPLIER_CODES)
        .get(code=supplier_code)
    )


def get_supplier_prices_queryset(*, supplier_code: str) -> QuerySet[SupplierOffer]:
    return (
        SupplierOffer.objects.select_related("supplier", "product", "product__brand")
        .filter(supplier__code=supplier_code)
        .order_by("product__name", "supplier_sku")
    )


def apply_supplier_prices_filters(*, queryset: QuerySet[SupplierOffer], query: str, availability: str) -> QuerySet[SupplierOffer]:
    if query:
        queryset = queryset.filter(
            Q(supplier_sku__icontains=query)
            | Q(product__sku__icontains=query)
            | Q(product__article__icontains=query)
            | Q(product__name__icontains=query)
            | Q(product__brand__name__icontains=query)
        )
    if availability in {"true", "1", "yes"}:
        queryset = queryset.filter(is_available=True)
    elif availability in {"false", "0", "no"}:
        queryset = queryset.filter(is_available=False)
    return queryset


def get_supplier_runs_queryset(*, supplier_code: str) -> QuerySet[ImportRun]:
    return (
        ImportRun.objects.select_related("source", "source__supplier")
        .filter(source__code=supplier_code)
        .order_by("-created_at")
    )


def get_supplier_errors_queryset(
    *,
    supplier_code: str,
    run_id: str = "",
    latest_only: bool = True,
) -> QuerySet[ImportRowError]:
    queryset = (
        ImportRowError.objects.select_related("run", "source")
        .filter(source__code=supplier_code)
        .order_by("-created_at")
    )
    if run_id:
        return queryset.filter(run_id=run_id)
    if not latest_only:
        return queryset

    latest_run = (
        ImportRun.objects.filter(source__code=supplier_code)
        .order_by("-created_at")
        .values_list("id", flat=True)
        .first()
    )
    if latest_run is None:
        return queryset.none()
    return queryset.filter(run_id=latest_run)
