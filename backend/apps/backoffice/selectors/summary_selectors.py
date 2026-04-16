from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, ImportRunQuality, ImportSource, SupplierRawOffer


def build_backoffice_summary_payload() -> dict:
    now = timezone.now()
    since_24h = now - timedelta(hours=24)

    latest_runs_qs = ImportRun.objects.select_related("source").order_by("-created_at")[:8]
    latest_runs = [
        {
            "id": str(run.id),
            "source_code": run.source.code,
            "source_name": run.source.name,
            "status": run.status,
            "dry_run": run.dry_run,
            "processed_rows": run.processed_rows,
            "errors_count": run.errors_count,
            "offers_created": run.offers_created,
            "offers_updated": run.offers_updated,
            "repriced_products": run.repriced_products,
            "finished_at": run.finished_at,
            "created_at": run.created_at,
        }
        for run in latest_runs_qs
    ]

    status_buckets = ImportRun.objects.values("status").annotate(total=Count("id")).order_by("status")

    totals = {
        "sources": ImportSource.objects.filter(is_active=True).count(),
        "import_runs": ImportRun.objects.count(),
        "errors_total": ImportRowError.objects.count(),
        "errors_24h": ImportRowError.objects.filter(created_at__gte=since_24h).count(),
        "raw_offers": SupplierRawOffer.objects.count(),
        "raw_offers_invalid": SupplierRawOffer.objects.filter(is_valid=False).count(),
        "unmatched_offers": SupplierRawOffer.objects.filter(match_status=SupplierRawOffer.MATCH_STATUS_UNMATCHED).count(),
        "conflict_offers": SupplierRawOffer.objects.filter(match_status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED).count(),
        "auto_matched_offers": SupplierRawOffer.objects.filter(match_status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED).count(),
        "manually_resolved_offers": SupplierRawOffer.objects.filter(match_status=SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED).count(),
        "supplier_offers": SupplierOffer.objects.count(),
        "product_prices": ProductPrice.objects.count(),
        "repriced_products_total": ImportRun.objects.aggregate(total=Sum("repriced_products")).get("total") or 0,
    }

    latest_completed_run = (
        ImportRun.objects.filter(status__in=[ImportRun.STATUS_SUCCESS, ImportRun.STATUS_PARTIAL]).order_by("-created_at").first()
    )
    quality_summary = {}
    if latest_completed_run is not None:
        processed_rows = max(latest_completed_run.processed_rows, 1)
        quality_summary = {
            "run_id": str(latest_completed_run.id),
            "source_code": latest_completed_run.source.code,
            "processed_rows": latest_completed_run.processed_rows,
            "errors_count": latest_completed_run.errors_count,
            "error_rate": round((latest_completed_run.errors_count / processed_rows) * 100, 2),
            "offers_created": latest_completed_run.offers_created,
            "offers_updated": latest_completed_run.offers_updated,
            "offers_skipped": latest_completed_run.offers_skipped,
        }

    quality_trend = [
        {
            "run_id": str(item.run_id),
            "source_code": item.source.code,
            "match_rate": float(item.match_rate),
            "error_rate": float(item.error_rate),
            "requires_operator_attention": item.requires_operator_attention,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in ImportRunQuality.objects.select_related("source").order_by("-created_at")[:20]
    ]

    match_rate_by_supplier = []
    seen_sources: set[str] = set()
    for item in ImportRunQuality.objects.select_related("source").order_by("-created_at"):
        source_id = str(item.source_id)
        if source_id in seen_sources:
            continue
        seen_sources.add(source_id)
        match_rate_by_supplier.append(
            {
                "source_code": item.source.code,
                "source_name": item.source.name,
                "match_rate": float(item.match_rate),
                "error_rate": float(item.error_rate),
                "status": item.status,
                "requires_operator_attention": item.requires_operator_attention,
            }
        )

    recent_failed_partial = [
        {
            "id": str(item.id),
            "source_code": item.source.code,
            "status": item.status,
            "errors_count": item.errors_count,
            "processed_rows": item.processed_rows,
            "created_at": item.created_at,
        }
        for item in ImportRun.objects.select_related("source")
        .filter(status__in=[ImportRun.STATUS_FAILED, ImportRun.STATUS_PARTIAL])
        .order_by("-created_at")[:10]
    ]

    degraded_items = []
    for item in ImportRunQuality.objects.select_related("source").order_by("-created_at")[:60]:
        codes = {str(flag.get("code")) for flag in (item.flags or []) if isinstance(flag, dict)}
        if "match_rate_drop" not in codes:
            continue
        degraded_items.append(item)
        if len(degraded_items) >= 10:
            break

    recent_degraded_imports = [
        {
            "run_id": str(item.run_id),
            "source_code": item.source.code,
            "status": item.status,
            "match_rate": float(item.match_rate),
            "error_rate": float(item.error_rate),
            "flags": item.flags,
            "created_at": item.created_at,
        }
        for item in degraded_items
    ]

    requires_operator_attention = [
        {
            "run_id": str(item.run_id),
            "source_code": item.source.code,
            "status": item.status,
            "flags": item.flags,
            "match_rate": float(item.match_rate),
            "error_rate": float(item.error_rate),
            "created_at": item.created_at,
        }
        for item in ImportRunQuality.objects.select_related("source")
        .filter(requires_operator_attention=True)
        .order_by("-created_at")[:12]
    ]

    return {
        "generated_at": now,
        "totals": totals,
        "status_buckets": list(status_buckets),
        "latest_runs": latest_runs,
        "quality_summary": quality_summary,
        "quality_trend": quality_trend,
        "match_rate_by_supplier": match_rate_by_supplier,
        "recent_failed_partial": recent_failed_partial,
        "recent_degraded_imports": recent_degraded_imports,
        "requires_operator_attention": requires_operator_attention,
    }
