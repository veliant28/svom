from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings

from apps.supplier_imports.models import ImportRun, ImportSource
from apps.supplier_imports.services.scheduling.cron_expression import CronExpression, compute_next_run
from apps.supplier_imports.tasks.import_supplier_file import import_supplier_file_task


@dataclass(frozen=True)
class ImportScheduleDispatchResult:
    source_code: str
    status: str
    task_id: str | None
    reason: str


class ScheduledImportService:
    def list_due_sources(self, *, now: datetime | None = None) -> list[ImportSource]:
        moment = now or datetime.utcnow().astimezone()
        due: list[ImportSource] = []
        queryset = (
            ImportSource.objects.filter(is_active=True, is_auto_import_enabled=True)
            .select_related("supplier")
            .order_by("name")
        )
        for source in queryset:
            if self.is_source_due(source=source, now=moment):
                due.append(source)
        return due

    def dispatch_due_sources(self, *, now: datetime | None = None) -> list[ImportScheduleDispatchResult]:
        results: list[ImportScheduleDispatchResult] = []
        for source in self.list_due_sources(now=now):
            if ImportRun.objects.filter(source=source, status=ImportRun.STATUS_RUNNING).exists():
                results.append(
                    ImportScheduleDispatchResult(
                        source_code=source.code,
                        status="skipped",
                        task_id=None,
                        reason="already_running",
                    )
                )
                continue

            task = import_supplier_file_task.delay(
                source_code=source.code,
                dry_run=False,
                trigger="beat:scheduled_import",
                reprice=source.auto_reprice_after_import,
                reindex=source.auto_reindex_after_import,
            )
            results.append(
                ImportScheduleDispatchResult(
                    source_code=source.code,
                    status="scheduled",
                    task_id=task.id,
                    reason="due",
                )
            )

        return results

    def is_source_due(self, *, source: ImportSource, now: datetime) -> bool:
        if not source.schedule_cron:
            return False

        timezone = self._resolve_timezone(source.schedule_timezone)
        if timezone is None:
            return False

        try:
            cron = CronExpression.parse(source.schedule_cron)
        except ValueError:
            return False

        local_now = now.astimezone(timezone).replace(second=0, microsecond=0)
        if not cron.matches(local_now):
            return False

        if source.last_started_at is None:
            return True

        last_local = source.last_started_at.astimezone(timezone).replace(second=0, microsecond=0)
        return last_local < local_now

    def get_next_run(self, *, source: ImportSource, now: datetime | None = None) -> datetime | None:
        timezone_name = source.schedule_timezone or settings.TIME_ZONE
        return compute_next_run(cron_expression=source.schedule_cron, timezone_name=timezone_name, now=now)

    def _resolve_timezone(self, timezone_name: str) -> ZoneInfo | None:
        try:
            return ZoneInfo(timezone_name or settings.TIME_ZONE)
        except ZoneInfoNotFoundError:
            return None
