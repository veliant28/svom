from __future__ import annotations

from typing import Any

from django.db import DatabaseError
from django.db.models import Count, OuterRef
from django.utils import timezone

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob, AutoDbRemoteQuotaState
from apps.autodb.selectors.admin_supplier_brands import get_admin_supplier_brand_name_by_id
from apps.autodb.services.matching.constants import REMOTE_QUOTA_KEY
from apps.catalog.models import AutoDbProductLinkQuality

PROTECTED_FIELDS = {
    "no_name_overwrite": True,
    "no_category_overwrite": True,
    "no_photo_overwrite": True,
    "no_price_stock_changes": True,
}


def safe_str(value: Any) -> str:
    return str(value or "").strip()


def parse_positive_int(value: Any, *, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def parse_bool(value: Any) -> bool | None:
    normalized = safe_str(value).lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def parse_supplier_id(value: Any) -> int | None:
    raw = safe_str(value)
    if not raw:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return None


def money_or_blank(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def supplier_display_name(supplier_id: int | None, fallback: str = "") -> str:
    if not supplier_id:
        return fallback
    try:
        return get_admin_supplier_brand_name_by_id(int(supplier_id)) or fallback or str(supplier_id)
    except DatabaseError:
        return fallback or str(supplier_id)


def status_counts(queryset) -> list[dict[str, Any]]:
    return [
        {"status": str(item["status"]), "count": int(item["count"] or 0)}
        for item in queryset.values("status").annotate(count=Count("id")).order_by("status")
    ]


def trusted_link_exists_queryset():
    return AutoDbProductLinkQuality.objects.filter(
        product_id=OuterRef("pk"),
        autodb_article_key=OuterRef("autodb_article_key"),
        status=AutoDbProductLinkQuality.STATUS_TRUSTED,
    )


def job_trusted_link_exists_queryset():
    return AutoDbProductLinkQuality.objects.filter(
        product_id=OuterRef("product_id"),
        status=AutoDbProductLinkQuality.STATUS_TRUSTED,
    )


def latest_evidence(job: AutoDbMatchJob) -> AutoDbMatchEvidence | None:
    prefetched = getattr(job, "backoffice_evidence", None)
    if prefetched:
        return prefetched[0]
    return job.evidence.order_by("-created_at").first()


def latest_evidence_for_stage(job: AutoDbMatchJob, stage: str) -> AutoDbMatchEvidence | None:
    prefetched = getattr(job, "backoffice_evidence", None)
    if prefetched:
        for item in prefetched:
            if item.stage == stage:
                return item
    return job.evidence.filter(stage=stage).order_by("-created_at").first()


def recommended_action(status_value: str) -> str:
    return {
        AutoDbMatchJob.STATUS_NEW: "run_local_dry_run",
        AutoDbMatchJob.STATUS_REMOTE_PENDING: "run_remote_with_limit",
        AutoDbMatchJob.STATUS_LOCAL_FOUND: "audit_link",
        AutoDbMatchJob.STATUS_REMOTE_FOUND: "audit_link",
        AutoDbMatchJob.STATUS_CLONE_SYNC_READY: "plan_clone_sync",
        AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE: "plan_safe_link",
        AutoDbMatchJob.STATUS_QUOTA_PAUSED: "wait_quota",
        AutoDbMatchJob.STATUS_NEEDS_REVIEW: "review",
        AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC: "skip_non_tecdoc",
        AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE: "review_article_source",
        AutoDbMatchJob.STATUS_SKIPPED_SPLIT_NEEDED: "split_needed",
        AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS: "review_ambiguous",
    }.get(status_value, "review")


def tecdoc_status(job: AutoDbMatchJob) -> str:
    if job.status == AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC:
        return "non_tecdoc"
    if job.resolved_supplier_id:
        return "tecdoc"
    return "unknown"


def quota_payload() -> dict[str, Any]:
    quota = AutoDbRemoteQuotaState.objects.filter(remote_key=REMOTE_QUOTA_KEY).first()
    now = timezone.now()
    if quota is None:
        return {
            "remote_key": REMOTE_QUOTA_KEY,
            "paused": False,
            "estimated_queries_used": 0,
            "cooldown_until": None,
            "last_ok_at": None,
            "last_quota_error_at": None,
            "last_error": "",
        }
    return {
        "remote_key": quota.remote_key,
        "paused": bool(quota.cooldown_until and quota.cooldown_until > now),
        "estimated_queries_used": int(quota.estimated_queries_used or 0),
        "cooldown_until": iso_or_none(quota.cooldown_until),
        "last_ok_at": iso_or_none(quota.last_ok_at),
        "last_quota_error_at": iso_or_none(quota.last_quota_error_at),
        "last_error": safe_str(quota.last_error),
    }


def jobs_for_action(request) -> list[AutoDbMatchJob]:
    ids = request.data.get("job_ids") or request.data.get("ids") or []
    if isinstance(ids, str):
        ids = [ids]
    limit = parse_positive_int(request.data.get("limit"), default=25, maximum=100)
    queryset = AutoDbMatchJob.objects.select_related("product").order_by("priority", "-created_at")
    if ids:
        queryset = queryset.filter(id__in=ids)
    return list(queryset[:limit])
