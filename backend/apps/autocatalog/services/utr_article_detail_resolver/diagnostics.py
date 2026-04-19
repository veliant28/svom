from __future__ import annotations

from apps.autocatalog.models import UtrArticleDetailMap
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

from .planner import count_raw_pairs
from .types import UtrArticleResolveProgress, UtrArticleResolveSummary


def collect_progress() -> UtrArticleResolveProgress:
    raw_pairs_total = count_raw_pairs()
    mapped_pairs_total = UtrArticleDetailMap.objects.count()
    mapped_pairs_resolved = UtrArticleDetailMap.objects.exclude(utr_detail_id="").count()
    mapped_pairs_unresolved = max(0, mapped_pairs_total - mapped_pairs_resolved)

    return UtrArticleResolveProgress(
        raw_pairs_total=raw_pairs_total,
        mapped_pairs_total=mapped_pairs_total,
        mapped_pairs_resolved=mapped_pairs_resolved,
        mapped_pairs_unresolved=mapped_pairs_unresolved,
        raw_pairs_unattempted=max(0, raw_pairs_total - mapped_pairs_total),
        raw_pairs_unresolved_total=max(0, raw_pairs_total - mapped_pairs_resolved),
    )


def classify_exception_kind(*, client, exc: SupplierClientError) -> str:
    if client.is_auth_error(exc):
        return "auth_failure"
    if client.is_transport_error(exc):
        return "transport_failure"
    return "supplier_error"


def classify_row_error_kind(*, error_message: str) -> str:
    message = str(error_message or "").strip().lower()
    if any(marker in message for marker in ("expired jwt token", "invalid jwt token", "unauthorized", "auth")):
        return "auth_failure"
    return "supplier_error"


def increment_stage_attempt_counter(*, summary: UtrArticleResolveSummary, stage_name: str) -> None:
    field_name = stage_counter_field(stage_name=stage_name, suffix="attempted_total")
    if not field_name:
        return
    setattr(summary, field_name, int(getattr(summary, field_name, 0)) + 1)


def increment_stage_resolved_counter(*, summary: UtrArticleResolveSummary, stage_name: str) -> None:
    field_name = stage_counter_field(stage_name=stage_name, suffix="resolved_total")
    if not field_name:
        return
    setattr(summary, field_name, int(getattr(summary, field_name, 0)) + 1)


def stage_counter_field(*, stage_name: str, suffix: str) -> str:
    normalized = str(stage_name or "").strip().lower()
    mapping = {
        "primary_brandless": f"stage_primary_brandless_{suffix}",
        "fallback_brandless": f"stage_fallback_brandless_{suffix}",
        "primary_branded": f"stage_primary_branded_{suffix}",
        "fallback_branded": f"stage_fallback_branded_{suffix}",
    }
    return mapping.get(normalized, "")
