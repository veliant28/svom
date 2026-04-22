from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db.models import Q
from django.utils import timezone as dj_timezone

from apps.supplier_imports.models import ImportRun, ImportSource
from apps.supplier_imports.services.scheduling.cron_expression import CronExpression, compute_next_run


@dataclass(frozen=True)
class ImportScheduleDispatchResult:
    source_code: str
    status: str
    task_id: str | None
    reason: str


class ScheduledImportService:
    DEFAULT_STALE_TIMEOUT_MINUTES = 180

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
        from apps.supplier_imports.tasks.run_scheduled_supplier_pipeline import run_scheduled_supplier_pipeline_task

        self.close_stale_running_runs(now=now)
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

            task = run_scheduled_supplier_pipeline_task.delay(
                source_code=source.code,
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

    def close_stale_running_runs(self, *, source: ImportSource | None = None, now: datetime | None = None) -> int:
        moment = now or dj_timezone.now()
        cutoff = moment - timedelta(minutes=self._stale_timeout_minutes())

        queryset = ImportRun.objects.filter(status=ImportRun.STATUS_RUNNING).filter(
            Q(started_at__lt=cutoff) | Q(started_at__isnull=True, created_at__lt=cutoff)
        )
        if source is not None:
            queryset = queryset.filter(source=source)

        closed = 0
        for run in queryset.select_related("source"):
            summary = dict(run.summary or {})
            summary["auto_closed"] = True
            summary["auto_closed_reason"] = "stale_running"
            summary["auto_closed_at"] = moment.isoformat()

            run.status = ImportRun.STATUS_FAILED
            run.finished_at = moment
            run.summary = summary
            run.note = ((run.note + "\n") if run.note else "") + "Auto-closed stale running import run."
            run.save(update_fields=("status", "finished_at", "summary", "note", "updated_at"))

            source_obj = run.source
            source_obj.last_finished_at = moment
            source_obj.last_failed_at = moment
            source_obj.save(update_fields=("last_finished_at", "last_failed_at", "updated_at"))
            closed += 1

        return closed

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
        start_date = self._resolve_schedule_start_date(source=source)
        if start_date and local_now.date() < start_date:
            return False
        if not cron.matches(local_now):
            return False

        if source.last_started_at is None:
            return True

        last_local = source.last_started_at.astimezone(timezone).replace(second=0, microsecond=0)
        return last_local < local_now

    def get_next_run(self, *, source: ImportSource, now: datetime | None = None) -> datetime | None:
        timezone_name = source.schedule_timezone or settings.TIME_ZONE
        timezone = self._resolve_timezone(timezone_name)
        if timezone is None:
            return None

        baseline = (now or datetime.now(tz=timezone)).astimezone(timezone)
        start_date = self._resolve_schedule_start_date(source=source)
        if start_date and baseline.date() < start_date:
            baseline = datetime.combine(start_date, time(hour=0, minute=0), tzinfo=timezone)

        return compute_next_run(
            cron_expression=source.schedule_cron,
            timezone_name=timezone_name,
            now=baseline,
        )

    def _resolve_timezone(self, timezone_name: str) -> ZoneInfo | None:
        try:
            return ZoneInfo(timezone_name or settings.TIME_ZONE)
        except ZoneInfoNotFoundError:
            return None

    def _resolve_schedule_start_date(self, *, source: ImportSource) -> date | None:
        parser_options = source.parser_options if isinstance(source.parser_options, dict) else {}
        raw_value = parser_options.get("schedule_start_date")
        if raw_value is None:
            return None
        try:
            return date.fromisoformat(str(raw_value))
        except ValueError:
            return None

    def _stale_timeout_minutes(self) -> int:
        raw = getattr(settings, "SUPPLIER_IMPORT_STALE_RUN_TIMEOUT_MINUTES", self.DEFAULT_STALE_TIMEOUT_MINUTES)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return self.DEFAULT_STALE_TIMEOUT_MINUTES
        return value if value > 0 else self.DEFAULT_STALE_TIMEOUT_MINUTES
