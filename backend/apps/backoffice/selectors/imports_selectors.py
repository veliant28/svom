from __future__ import annotations

from datetime import datetime

from django.db.models import F
from django.db.models import QuerySet

from apps.supplier_imports.models import ImportArtifact, ImportRowError, ImportRun, ImportSource, SupplierRawOffer


def get_import_sources_queryset() -> QuerySet[ImportSource]:
    return ImportSource.objects.select_related("supplier").order_by("name")


def get_import_runs_queryset() -> QuerySet[ImportRun]:
    return ImportRun.objects.select_related("source", "source__supplier").order_by("-created_at")


def get_import_artifacts_queryset() -> QuerySet[ImportArtifact]:
    return ImportArtifact.objects.select_related("run", "source").order_by("-created_at")


def get_import_errors_queryset() -> QuerySet[ImportRowError]:
    return ImportRowError.objects.select_related("run", "source", "artifact").order_by("-created_at")


def get_import_raw_offers_queryset() -> QuerySet[SupplierRawOffer]:
    return SupplierRawOffer.objects.select_related(
        "source",
        "supplier",
        "run",
        "artifact",
        "matched_product",
        "matched_product__category",
        "mapped_category",
        "mapped_category__parent",
    ).order_by("-created_at")


def apply_import_run_filters(queryset: QuerySet[ImportRun], *, params) -> QuerySet[ImportRun]:
    status = params.get("status", "").strip()
    source_code = params.get("source", "").strip()
    dry_run = params.get("dry_run", "").strip().lower()
    date_from = params.get("date_from", "").strip()
    date_to = params.get("date_to", "").strip()

    if status:
        queryset = queryset.filter(status=status)
    if source_code:
        queryset = queryset.filter(source__code=source_code)
    if dry_run in {"true", "1", "yes"}:
        queryset = queryset.filter(dry_run=True)
    elif dry_run in {"false", "0", "no"}:
        queryset = queryset.filter(dry_run=False)

    if date_from:
        try:
            queryset = queryset.filter(created_at__date__gte=datetime.fromisoformat(date_from).date())
        except ValueError:
            pass
    if date_to:
        try:
            queryset = queryset.filter(created_at__date__lte=datetime.fromisoformat(date_to).date())
        except ValueError:
            pass

    return queryset


def apply_import_error_filters(queryset: QuerySet[ImportRowError], *, params) -> QuerySet[ImportRowError]:
    source_code = params.get("source", "").strip()
    run_id = params.get("run_id", "").strip()
    error_code = params.get("error_code", "").strip()
    date_from = params.get("date_from", "").strip()
    date_to = params.get("date_to", "").strip()

    if source_code:
        queryset = queryset.filter(source__code=source_code)
    if run_id:
        queryset = queryset.filter(run_id=run_id)
    if error_code:
        queryset = queryset.filter(error_code=error_code)

    if date_from:
        try:
            queryset = queryset.filter(created_at__date__gte=datetime.fromisoformat(date_from).date())
        except ValueError:
            pass
    if date_to:
        try:
            queryset = queryset.filter(created_at__date__lte=datetime.fromisoformat(date_to).date())
        except ValueError:
            pass

    return queryset


def apply_import_raw_offer_filters(queryset: QuerySet[SupplierRawOffer], *, params) -> QuerySet[SupplierRawOffer]:
    source_code = params.get("source", "").strip()
    supplier_code = params.get("supplier", "").strip()
    run_id = params.get("run_id", "").strip()
    validity = params.get("is_valid", "").strip().lower()
    match_status = params.get("match_status", "").strip()
    match_reason = params.get("match_reason", "").strip()
    brand = params.get("brand", "").strip()
    category_mapping_status = params.get("category_mapping_status", "").strip()
    category_mapping_reason = params.get("category_mapping_reason", "").strip()
    mapped_category = params.get("mapped_category", "").strip()
    ordering = params.get("ordering", "").strip()
    date_from = params.get("date_from", "").strip()
    date_to = params.get("date_to", "").strip()

    if source_code:
        queryset = queryset.filter(source__code=source_code)
    if supplier_code:
        queryset = queryset.filter(supplier__code=supplier_code)
    if run_id:
        queryset = queryset.filter(run_id=run_id)
    if match_status:
        queryset = queryset.filter(match_status=match_status)
    if match_reason:
        queryset = queryset.filter(match_reason=match_reason)
    if brand:
        queryset = queryset.filter(brand_name__icontains=brand)
    if category_mapping_status:
        queryset = queryset.filter(category_mapping_status=category_mapping_status)
    if category_mapping_reason:
        queryset = queryset.filter(category_mapping_reason=category_mapping_reason)
    if mapped_category:
        queryset = queryset.filter(mapped_category_id=mapped_category)

    if validity in {"true", "1", "yes"}:
        queryset = queryset.filter(is_valid=True)
    elif validity in {"false", "0", "no"}:
        queryset = queryset.filter(is_valid=False)

    if date_from:
        try:
            queryset = queryset.filter(created_at__date__gte=datetime.fromisoformat(date_from).date())
        except ValueError:
            pass
    if date_to:
        try:
            queryset = queryset.filter(created_at__date__lte=datetime.fromisoformat(date_to).date())
        except ValueError:
            pass

    if ordering == "confidence_desc":
        queryset = queryset.order_by(F("category_mapping_confidence").desc(nulls_last=True), "-updated_at")
    elif ordering == "confidence_asc":
        queryset = queryset.order_by(F("category_mapping_confidence").asc(nulls_last=True), "-updated_at")
    elif ordering == "reason":
        queryset = queryset.order_by("category_mapping_reason", "-updated_at")
    elif ordering == "-reason":
        queryset = queryset.order_by("-category_mapping_reason", "-updated_at")
    elif ordering == "category":
        queryset = queryset.order_by("mapped_category__name", "-updated_at")
    elif ordering == "-category":
        queryset = queryset.order_by("-mapped_category__name", "-updated_at")
    elif ordering == "created_at":
        queryset = queryset.order_by("created_at")
    elif ordering == "-created_at":
        queryset = queryset.order_by("-created_at")

    return queryset


def get_unmatched_raw_offers_queryset() -> QuerySet[SupplierRawOffer]:
    return get_import_raw_offers_queryset().filter(match_status=SupplierRawOffer.MATCH_STATUS_UNMATCHED)


def get_conflict_raw_offers_queryset() -> QuerySet[SupplierRawOffer]:
    return get_import_raw_offers_queryset().filter(match_status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED)
