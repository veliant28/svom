from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from django.utils import timezone

from apps.supplier_imports.models import ImportArtifact, ImportRowError, ImportRun, ImportSource
from apps.supplier_imports.services.quality import ImportQualityService
from apps.supplier_imports.services.integrations.integration_state_service import SupplierIntegrationStateService

from .categorized_mapping_import_service import (
    CategorizedImportStats,
    CategorizedSupplierCategoryImportService,
)


@dataclass(frozen=True)
class CategorizedOperationalRunResult:
    source_code: str
    run_id: str
    run_status: str
    stats: CategorizedImportStats
    category_status_counts: dict[str, int]


class CategorizedMappingOperationalImportService:
    def __init__(self, *, batch_size: int = 1000) -> None:
        self._import_service = CategorizedSupplierCategoryImportService(batch_size=batch_size)
        self._quality_service = ImportQualityService()
        self._integration_state = SupplierIntegrationStateService()

    def run_for_source(
        self,
        *,
        source: ImportSource,
        file_paths: list[Path],
        supplier_code: str,
        dry_run: bool = False,
        strict_supplier_match: bool = True,
    ) -> CategorizedOperationalRunResult:
        started_at = timezone.now()
        run = ImportRun.objects.create(
            source=source,
            status=ImportRun.STATUS_RUNNING,
            trigger="command:import_categorized_supplier_prices",
            dry_run=dry_run,
            started_at=started_at,
            summary={
                "mode": "categorized_xlsx_import",
                "quality_mode": "category_mapping",
                "supplier_code": supplier_code,
                "files": [str(path) for path in file_paths],
            },
        )
        self._update_source_started(source=source, started_at=started_at)

        try:
            stats = self._import_service.import_from_files(
                file_paths=file_paths,
                supplier_filter={supplier_code},
                strict_supplier_match=strict_supplier_match,
            )
            self._create_artifacts(run=run, source=source, file_paths=file_paths, stats=stats)
            self._create_row_errors(run=run, source=source, stats=stats)

            category_status_counts = self._import_service.get_source_category_status_counts(supplier_code=supplier_code)
            total_rows = max(int(stats.rows_parsed), 0)
            summary = {
                "mode": "categorized_xlsx_import",
                "quality_mode": "category_mapping",
                "supplier_code": supplier_code,
                "files": [str(path) for path in file_paths],
                "rows_total": int(stats.rows_total),
                "rows_parsed": int(stats.rows_parsed),
                "rows_mapped": int(stats.rows_mapped),
                "rows_updated": int(stats.rows_updated),
                "rows_unchanged": int(stats.rows_unchanged),
                "rows_skipped_invalid": int(stats.rows_skipped_invalid),
                "rows_skipped_duplicate": int(stats.rows_skipped_duplicate),
                "rows_skipped_supplier_filter": int(stats.rows_skipped_supplier_filter),
                "rows_not_found": int(stats.rows_not_found),
                "rows_supplier_mismatch": int(stats.rows_supplier_mismatch),
                "rows_unresolved_category": int(stats.rows_unresolved_category),
                "mappings_overwritten": int(stats.mappings_overwritten),
                "categories_created": int(stats.categories_created),
                "categories_reactivated": int(stats.categories_reactivated),
                "category_total_rows": int(sum(category_status_counts.values()) or total_rows),
                "category_status_counts": category_status_counts,
                "file_summaries": stats.file_summaries,
            }

            run.processed_rows = total_rows
            run.parsed_rows = total_rows
            run.offers_created = 0
            run.offers_updated = int(stats.rows_updated)
            run.offers_skipped = int(
                stats.rows_unchanged
                + stats.rows_skipped_invalid
                + stats.rows_skipped_duplicate
                + stats.rows_skipped_supplier_filter
            )
            run.errors_count = int(stats.errors_count)
            run.status = self._resolve_run_status(stats=stats)
            run.finished_at = timezone.now()
            run.summary = summary
            run.note = ""
            run.save(
                update_fields=(
                    "status",
                    "finished_at",
                    "processed_rows",
                    "parsed_rows",
                    "offers_created",
                    "offers_updated",
                    "offers_skipped",
                    "errors_count",
                    "summary",
                    "note",
                    "updated_at",
                )
            )
            self._quality_service.refresh_for_run(run=run)
            self._update_source_finished(source=source, run=run)
            self._mark_integration_state(source=source, run=run)
        except Exception as exc:
            run.status = ImportRun.STATUS_FAILED
            run.finished_at = timezone.now()
            run.note = str(exc)[:1000]
            run.summary = {
                **(run.summary or {}),
                "exception": str(exc),
            }
            run.save(update_fields=("status", "finished_at", "note", "summary", "updated_at"))
            self._update_source_finished(source=source, run=run)
            self._mark_integration_state(source=source, run=run)
            self._quality_service.refresh_for_run(run=run)
            raise

        return CategorizedOperationalRunResult(
            source_code=source.code,
            run_id=str(run.id),
            run_status=run.status,
            stats=stats,
            category_status_counts=category_status_counts,
        )

    def _create_artifacts(
        self,
        *,
        run: ImportRun,
        source: ImportSource,
        file_paths: list[Path],
        stats: CategorizedImportStats,
    ) -> None:
        by_name = {str(item.get("file_name") or ""): item for item in stats.file_summaries}
        artifacts: list[ImportArtifact] = []

        for file_path in file_paths:
            file_stats = by_name.get(file_path.name, {})
            file_bytes = file_path.read_bytes()
            checksum_sha1 = hashlib.sha1(file_bytes).hexdigest()  # noqa: S324
            rows_kept = int(file_stats.get("rows_kept") or 0)
            rows_invalid = int(file_stats.get("rows_invalid") or 0)
            rows_duplicate_file = int(file_stats.get("rows_duplicate_file") or 0)

            artifact_status = ImportArtifact.STATUS_PROCESSED if rows_kept > 0 else ImportArtifact.STATUS_SKIPPED
            if rows_invalid > 0 and rows_kept <= 0:
                artifact_status = ImportArtifact.STATUS_FAILED

            artifacts.append(
                ImportArtifact(
                    run=run,
                    source=source,
                    file_name=file_path.name,
                    file_path=str(file_path),
                    file_format=file_path.suffix.lstrip(".").lower(),
                    file_size=len(file_bytes),
                    checksum_sha1=checksum_sha1,
                    status=artifact_status,
                    parsed_rows=max(rows_kept, 0),
                    errors_count=max(rows_invalid + rows_duplicate_file, 0),
                )
            )

        if artifacts:
            ImportArtifact.objects.bulk_create(artifacts, batch_size=200)

    def _create_row_errors(self, *, run: ImportRun, source: ImportSource, stats: CategorizedImportStats) -> None:
        if not stats.row_issues:
            return
        rows = [
            ImportRowError(
                run=run,
                source=source,
                artifact=None,
                row_number=item.row_number,
                external_sku=item.article[:128],
                error_code=item.error_code[:64],
                message=item.message[:2000],
                raw_payload={
                    "source_row_id": item.raw_offer_id,
                    "file_name": item.file_name,
                    "supplier_code": item.supplier_code,
                },
            )
            for item in stats.row_issues
        ]
        ImportRowError.objects.bulk_create(rows, batch_size=500)

    def _resolve_run_status(self, *, stats: CategorizedImportStats) -> str:
        if stats.rows_parsed <= 0 and stats.errors_count > 0:
            return ImportRun.STATUS_FAILED
        if stats.errors_count > 0:
            return ImportRun.STATUS_PARTIAL
        return ImportRun.STATUS_SUCCESS

    @staticmethod
    def _update_source_started(*, source: ImportSource, started_at) -> None:
        source.last_started_at = started_at
        source.save(update_fields=("last_started_at", "updated_at"))

    @staticmethod
    def _update_source_finished(*, source: ImportSource, run: ImportRun) -> None:
        source.last_finished_at = run.finished_at
        if run.status in {ImportRun.STATUS_SUCCESS, ImportRun.STATUS_PARTIAL}:
            source.last_success_at = run.finished_at
        if run.status == ImportRun.STATUS_FAILED:
            source.last_failed_at = run.finished_at
        source.save(update_fields=("last_finished_at", "last_success_at", "last_failed_at", "updated_at"))

    def _mark_integration_state(self, *, source: ImportSource, run: ImportRun) -> None:
        integration = self._integration_state.get_for_source(source=source)
        if run.status in {ImportRun.STATUS_SUCCESS, ImportRun.STATUS_PARTIAL}:
            self._integration_state.mark_import_success(integration=integration)
            return
        self._integration_state.mark_import_failure(integration=integration, message=run.note or "categorized import failed")
