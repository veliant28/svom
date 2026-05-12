from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from django.core.management.base import CommandError
from django.utils import timezone

from apps.autodb.models import AutoDbMatchingRun
from apps.autodb.services.matching.reports import write_report


class MatchingCommandMixin:
    command_name = ""

    def add_common_arguments(self, parser, *, default_limit: int = 100, dry_run_default: bool = True) -> None:
        parser.add_argument("--limit", type=int, default=default_limit)
        parser.add_argument("--dry-run", action="store_true", default=dry_run_default)
        parser.add_argument("--export-prefix", type=str, default="")

    def start_run(self, *, run_type: str, dry_run: bool) -> AutoDbMatchingRun:
        return AutoDbMatchingRun.objects.create(
            run_type=run_type,
            status=AutoDbMatchingRun.STATUS_RUNNING,
            dry_run=dry_run,
            started_at=timezone.now(),
            created_by_source=f"management:{run_type}",
        )

    def finish_run(self, run: AutoDbMatchingRun, *, rows_count: int, status: str = AutoDbMatchingRun.STATUS_SUCCESS, **summary: Any) -> None:
        run.status = status
        run.finished_at = timezone.now()
        run.summary_json = {"rows": rows_count, **summary}
        run.save(update_fields=["status", "finished_at", "summary_json", "updated_at"])

    def fail_run(self, run: AutoDbMatchingRun, exc: Exception) -> None:
        run.status = AutoDbMatchingRun.STATUS_FAILED
        run.finished_at = timezone.now()
        run.error = str(exc)
        run.save(update_fields=["status", "finished_at", "error", "updated_at"])

    def export(self, *, run: AutoDbMatchingRun, rows, title: str, export_prefix: str = "", **summary: Any):
        materialized = [self.row_to_dict(row) for row in rows]
        csv_path, md_path, rows_count = write_report(
            command_name=self.command_name,
            run_id=str(run.id),
            rows=materialized,
            title=title,
            summary={"run_id": run.id, "dry_run": run.dry_run, **summary},
            export_prefix=export_prefix or None,
        )
        return csv_path, md_path, rows_count

    def row_to_dict(self, row) -> dict[str, Any]:
        if is_dataclass(row):
            return asdict(row)
        if isinstance(row, dict):
            return dict(row)
        return {key: value for key, value in vars(row).items() if not key.startswith("_")}

    def require_apply(self, options: dict[str, Any]) -> None:
        if not options.get("apply"):
            raise CommandError("--apply is required for this command")
