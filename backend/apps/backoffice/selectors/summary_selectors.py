from __future__ import annotations

import sys
from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from apps.catalog.models import Product
from apps.commerce.models import Order
from apps.pricing.models import PriceHistory, ProductPrice, SupplierOffer
from apps.supplier_imports.models import ImportRowError, ImportRun, ImportRunQuality, ImportSource, SupplierRawOffer


SUMMARY_AGGREGATE_CACHE_SECONDS = 30


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

    aggregate_stats = _get_summary_aggregate_stats(since_24h=since_24h)
    totals = aggregate_stats["totals"]
    orders_unprocessed = aggregate_stats["orders_unprocessed"]
    status_buckets = aggregate_stats["status_buckets"]

    latest_completed_run = (
        ImportRun.objects.select_related("source")
        .filter(status__in=[ImportRun.STATUS_SUCCESS, ImportRun.STATUS_PARTIAL])
        .order_by("-created_at")
        .first()
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

    latest_quality_per_supplier = (
        ImportRunQuality.objects.select_related("source")
        .annotate(
            source_row=Window(
                expression=RowNumber(),
                partition_by=[F("source_id")],
                order_by=F("created_at").desc(),
            )
        )
        .filter(source_row=1)
        .order_by("-created_at")
    )
    match_rate_by_supplier = []
    for item in latest_quality_per_supplier:
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
        "orders_unprocessed": orders_unprocessed,
        "status_buckets": status_buckets,
        "latest_runs": latest_runs,
        "quality_summary": quality_summary,
        "quality_trend": quality_trend,
        "match_rate_by_supplier": match_rate_by_supplier,
        "recent_failed_partial": recent_failed_partial,
        "recent_degraded_imports": recent_degraded_imports,
        "requires_operator_attention": requires_operator_attention,
    }


def _get_summary_aggregate_stats(*, since_24h) -> dict:
    cache_key = _summary_aggregate_cache_key()
    if cache_key:
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

    status_buckets = list(ImportRun.objects.values("status").annotate(total=Count("id")).order_by("status"))
    import_runs_total = sum(int(row["total"] or 0) for row in status_buckets)
    repriced_stats = PriceHistory.objects.filter(source=PriceHistory.SOURCE_IMPORT).aggregate(
        total=Count("product_id", distinct=True),
        last_24h=Count("product_id", filter=Q(created_at__gte=since_24h), distinct=True),
    )
    unprocessed_statuses = (
        Order.STATUS_NEW,
        Order.STATUS_PROCESSING,
        Order.STATUS_READY_FOR_SHIPMENT,
    )
    unprocessed_orders_qs = Order.objects.filter(status__in=unprocessed_statuses)
    unprocessed_order_stats = unprocessed_orders_qs.aggregate(total=Count("id"))
    unprocessed_oldest = (
        unprocessed_orders_qs.order_by("placed_at", "created_at")
        .values("placed_at", "order_number")
        .first()
    )
    import_error_stats = ImportRowError.objects.aggregate(
        total=Count("id"),
        last_24h=Count("id", filter=Q(created_at__gte=since_24h)),
    )
    raw_offer_stats = SupplierRawOffer.objects.aggregate(
        total=Count("id"),
        invalid=Count("id", filter=Q(is_valid=False)),
        unmatched=Count("id", filter=Q(match_status=SupplierRawOffer.MATCH_STATUS_UNMATCHED)),
        conflict=Count("id", filter=Q(match_status=SupplierRawOffer.MATCH_STATUS_MANUAL_REQUIRED)),
        auto_matched=Count("id", filter=Q(match_status=SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED)),
        manually_resolved=Count("id", filter=Q(match_status=SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED)),
    )

    payload = {
        "totals": {
            "sources": ImportSource.objects.filter(is_active=True).count(),
            "import_runs": import_runs_total,
            "errors_total": import_error_stats["total"] or 0,
            "errors_24h": import_error_stats["last_24h"] or 0,
            "raw_offers": raw_offer_stats["total"] or 0,
            "raw_offers_invalid": raw_offer_stats["invalid"] or 0,
            "unmatched_offers": raw_offer_stats["unmatched"] or 0,
            "conflict_offers": raw_offer_stats["conflict"] or 0,
            "auto_matched_offers": raw_offer_stats["auto_matched"] or 0,
            "manually_resolved_offers": raw_offer_stats["manually_resolved"] or 0,
            "supplier_offers": SupplierOffer.objects.count(),
            "published_products": Product.objects.filter(is_active=True).count(),
            "product_prices": ProductPrice.objects.count(),
            "repriced_products_total": repriced_stats["total"] or 0,
            "repriced_products_24h": repriced_stats["last_24h"] or 0,
        },
        "orders_unprocessed": {
            "count": unprocessed_order_stats["total"] or 0,
            "oldest_created_at": (unprocessed_oldest["placed_at"] if unprocessed_oldest else None),
            "oldest_order_number": (unprocessed_oldest["order_number"] if unprocessed_oldest else ""),
        },
        "status_buckets": status_buckets,
    }
    if cache_key:
        cache.set(cache_key, payload, SUMMARY_AGGREGATE_CACHE_SECONDS)
    return payload


def _summary_aggregate_cache_key() -> str:
    if _is_running_tests():
        return ""
    database_name = str(connection.settings_dict.get("NAME") or connection.alias)
    return f"backoffice:summary:aggregates:{database_name}:v1"


def _is_running_tests() -> bool:
    return any(arg == "test" or arg.endswith("/test") for arg in sys.argv)
