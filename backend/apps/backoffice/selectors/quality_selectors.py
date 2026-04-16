from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from apps.supplier_imports.models import ImportRun, ImportRunQuality


def get_import_quality_queryset():
    return ImportRunQuality.objects.select_related("run", "source", "previous_run").order_by("-created_at")


def build_import_quality_summary_payload() -> dict:
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    queryset = get_import_quality_queryset()

    totals = {
        "total_quality_runs": queryset.count(),
        "attention_runs": queryset.filter(requires_operator_attention=True).count(),
        "failed_runs": queryset.filter(status=ImportRun.STATUS_FAILED).count(),
        "partial_runs": queryset.filter(status=ImportRun.STATUS_PARTIAL).count(),
        "avg_match_rate": float(queryset.aggregate(value=Avg("match_rate")).get("value") or 0),
        "avg_error_rate": float(queryset.aggregate(value=Avg("error_rate")).get("value") or 0),
        "attention_runs_24h": queryset.filter(requires_operator_attention=True, created_at__gte=since_24h).count(),
    }

    latest_by_supplier = []
    seen_sources: set[str] = set()
    for quality in queryset:
        source_id = str(quality.source_id)
        if source_id in seen_sources:
            continue
        seen_sources.add(source_id)
        latest_by_supplier.append(
            {
                "source_code": quality.source.code,
                "source_name": quality.source.name,
                "match_rate": float(quality.match_rate),
                "error_rate": float(quality.error_rate),
                "status": quality.status,
                "requires_operator_attention": quality.requires_operator_attention,
            }
        )

    attention_runs = [
        {
            "run_id": str(item.run_id),
            "source_code": item.source.code,
            "status": item.status,
            "match_rate": float(item.match_rate),
            "error_rate": float(item.error_rate),
            "flags": item.flags,
            "created_at": item.created_at,
        }
        for item in queryset.filter(requires_operator_attention=True)[:12]
    ]

    return {
        "generated_at": now,
        "totals": totals,
        "latest_by_supplier": latest_by_supplier,
        "attention_runs": attention_runs,
    }


def build_run_quality_comparison_payload(*, run: ImportRun) -> dict:
    try:
        current = run.quality
    except ImportRunQuality.DoesNotExist:
        current = None
    previous_run = current.previous_run if current else None
    previous = None
    if previous_run is not None:
        try:
            previous = previous_run.quality
        except ImportRunQuality.DoesNotExist:
            previous = None

    if current is None:
        return {
            "run_id": str(run.id),
            "source_code": run.source.code,
            "current": None,
            "previous": None,
            "delta": {"match_rate": 0.0, "error_rate": 0.0},
            "flags": [],
            "requires_operator_attention": False,
        }

    return {
        "run_id": str(run.id),
        "source_code": run.source.code,
        "current": _serialize(current),
        "previous": _serialize(previous) if previous else None,
        "delta": {
            "match_rate": float(current.match_rate_delta),
            "error_rate": float(current.error_rate_delta),
        },
        "flags": current.flags,
        "requires_operator_attention": current.requires_operator_attention,
    }


def _serialize(item: ImportRunQuality) -> dict:
    return {
        "run_id": str(item.run_id),
        "status": item.status,
        "total_rows": item.total_rows,
        "matched_rows": item.matched_rows,
        "auto_matched_rows": item.auto_matched_rows,
        "manual_matched_rows": item.manual_matched_rows,
        "ignored_rows": item.ignored_rows,
        "unmatched_rows": item.unmatched_rows,
        "conflict_rows": item.conflict_rows,
        "error_rows": item.error_rows,
        "match_rate": float(item.match_rate),
        "error_rate": float(item.error_rate),
        "match_rate_delta": float(item.match_rate_delta),
        "error_rate_delta": float(item.error_rate_delta),
        "flags": item.flags,
        "requires_operator_attention": item.requires_operator_attention,
        "created_at": item.created_at,
    }
