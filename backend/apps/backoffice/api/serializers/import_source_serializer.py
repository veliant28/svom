from __future__ import annotations

from datetime import time

from rest_framework import serializers

from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services import ScheduledImportService


class ImportSourceSerializer(serializers.ModelSerializer):
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    last_run = serializers.SerializerMethodField()
    next_run = serializers.SerializerMethodField()
    schedule_start_date = serializers.SerializerMethodField()
    schedule_run_time = serializers.SerializerMethodField()
    schedule_every_day = serializers.SerializerMethodField()

    class Meta:
        model = ImportSource
        fields = (
            "id",
            "code",
            "name",
            "supplier_code",
            "supplier_name",
            "parser_type",
            "input_path",
            "file_patterns",
            "default_currency",
            "auto_reprice",
            "auto_reindex",
            "is_auto_import_enabled",
            "schedule_cron",
            "schedule_timezone",
            "schedule_start_date",
            "schedule_run_time",
            "schedule_every_day",
            "auto_reprice_after_import",
            "auto_reindex_after_import",
            "last_started_at",
            "last_finished_at",
            "last_success_at",
            "last_failed_at",
            "is_active",
            "last_run",
            "next_run",
            "created_at",
            "updated_at",
        )

    def get_last_run(self, obj: ImportSource):
        run = obj.runs.first()
        if run is None:
            return None

        return {
            "id": str(run.id),
            "status": run.status,
            "processed_rows": run.processed_rows,
            "errors_count": run.errors_count,
            "offers_created": run.offers_created,
            "offers_updated": run.offers_updated,
            "finished_at": run.finished_at,
            "created_at": run.created_at,
        }

    def get_next_run(self, obj: ImportSource):
        if not obj.is_active or not obj.is_auto_import_enabled:
            return None
        return ScheduledImportService().get_next_run(source=obj)

    def get_schedule_start_date(self, obj: ImportSource) -> str | None:
        parser_options = obj.parser_options if isinstance(obj.parser_options, dict) else {}
        value = parser_options.get("schedule_start_date")
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def get_schedule_run_time(self, obj: ImportSource) -> str:
        run_time = _extract_schedule_time_from_cron(obj.schedule_cron)
        return run_time.strftime("%H:%M")

    def get_schedule_every_day(self, obj: ImportSource) -> bool:
        parts = str(obj.schedule_cron or "").split()
        if len(parts) != 5:
            return True
        return parts[2] == "*" and parts[3] == "*" and parts[4] == "*"


def _extract_schedule_time_from_cron(cron_expression: str) -> time:
    parts = str(cron_expression or "").split()
    if len(parts) != 5:
        return time(hour=1, minute=0)

    minute_raw, hour_raw = parts[0], parts[1]
    if not minute_raw.isdigit() or not hour_raw.isdigit():
        return time(hour=1, minute=0)

    minute = int(minute_raw)
    hour = int(hour_raw)
    if minute < 0 or minute > 59 or hour < 0 or hour > 23:
        return time(hour=1, minute=0)

    return time(hour=hour, minute=minute)
