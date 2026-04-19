from __future__ import annotations

from django.utils import timezone

from apps.supplier_imports.models import ImportRun, ImportSource

from .types import ImportExecutionResult


def resolve_run_status(*, run: ImportRun) -> str:
    if run.parsed_rows == 0 and run.errors_count > 0:
        return ImportRun.STATUS_FAILED
    if run.parsed_rows == 0:
        return ImportRun.STATUS_FAILED
    if run.errors_count > 0:
        return ImportRun.STATUS_PARTIAL
    return ImportRun.STATUS_SUCCESS


def as_result(*, run: ImportRun) -> ImportExecutionResult:
    summary = {
        "processed_rows": run.processed_rows,
        "parsed_rows": run.parsed_rows,
        "offers_created": run.offers_created,
        "offers_updated": run.offers_updated,
        "offers_skipped": run.offers_skipped,
        "errors_count": run.errors_count,
        "repriced_products": run.repriced_products,
        "reindexed_products": run.reindexed_products,
        "dry_run": run.dry_run,
        **(run.summary or {}),
    }
    return ImportExecutionResult(
        run_id=str(run.id),
        source_code=run.source.code,
        status=run.status,
        summary=summary,
    )


def finalize_source_timestamps(*, source: ImportSource, run: ImportRun) -> None:
    finished_at = run.finished_at or timezone.now()
    source.last_finished_at = finished_at
    if run.status in {ImportRun.STATUS_SUCCESS, ImportRun.STATUS_PARTIAL}:
        source.last_success_at = finished_at
    if run.status == ImportRun.STATUS_FAILED:
        source.last_failed_at = finished_at
    source.save(
        update_fields=(
            "last_finished_at",
            "last_success_at",
            "last_failed_at",
            "updated_at",
        )
    )
