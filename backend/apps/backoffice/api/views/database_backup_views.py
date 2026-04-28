from __future__ import annotations

from datetime import time

from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.core.models import DatabaseBackupSettings
from apps.core.selectors.database_backup_selectors import get_database_backup_settings
from apps.core.services.database_backup import DatabaseBackupService


class DatabaseBackupSettingsSerializer(serializers.ModelSerializer):
    schedule_run_time = serializers.SerializerMethodField()
    schedule_every_day = serializers.SerializerMethodField()
    next_run = serializers.SerializerMethodField()
    last_backup_filename = serializers.SerializerMethodField()

    class Meta:
        model = DatabaseBackupSettings
        fields = (
            "id",
            "code",
            "is_enabled",
            "schedule_cron",
            "schedule_timezone",
            "schedule_run_time",
            "schedule_every_day",
            "backup_directory",
            "retention_count",
            "last_started_at",
            "last_finished_at",
            "last_success_at",
            "last_failed_at",
            "last_status",
            "last_message",
            "last_backup_path",
            "last_backup_filename",
            "last_backup_size",
            "next_run",
            "created_at",
            "updated_at",
        )

    def get_schedule_run_time(self, obj: DatabaseBackupSettings) -> str:
        return _extract_schedule_time_from_cron(obj.schedule_cron).strftime("%H:%M")

    def get_schedule_every_day(self, obj: DatabaseBackupSettings) -> bool:
        parts = str(obj.schedule_cron or "").split()
        return len(parts) == 5 and parts[2:] == ["*", "*", "*"]

    def get_next_run(self, obj: DatabaseBackupSettings):
        return DatabaseBackupService().get_next_run(backup_settings=obj)

    def get_last_backup_filename(self, obj: DatabaseBackupSettings) -> str:
        return obj.last_backup_path.rsplit("/", maxsplit=1)[-1] if obj.last_backup_path else ""


class DatabaseBackupSettingsUpdateSerializer(serializers.ModelSerializer):
    schedule_run_time = serializers.TimeField(
        required=False,
        format="%H:%M",
        input_formats=("%H:%M", "%H:%M:%S"),
        write_only=True,
    )
    schedule_every_day = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = DatabaseBackupSettings
        fields = (
            "is_enabled",
            "schedule_cron",
            "schedule_timezone",
            "schedule_run_time",
            "schedule_every_day",
            "backup_directory",
            "retention_count",
        )

    def validate_retention_count(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError("Retention should be at least 1 backup.")
        return value

    def validate(self, attrs):
        if "schedule_every_day" in attrs and attrs.get("schedule_every_day") is False:
            raise serializers.ValidationError({"schedule_every_day": "Only daily schedule mode is supported."})
        return attrs

    def update(self, instance, validated_data):
        has_schedule_cron = "schedule_cron" in validated_data
        has_schedule_run_time = "schedule_run_time" in validated_data
        has_schedule_every_day = "schedule_every_day" in validated_data
        run_time = validated_data.pop("schedule_run_time", serializers.empty)
        validated_data.pop("schedule_every_day", None)

        if has_schedule_cron or has_schedule_run_time or has_schedule_every_day:
            if run_time is serializers.empty:
                run_time = _extract_schedule_time_from_cron(
                    str(validated_data.get("schedule_cron") or instance.schedule_cron)
                )
            validated_data["schedule_cron"] = f"{run_time.minute} {run_time.hour} * * *"

        if not validated_data.get("schedule_timezone"):
            validated_data["schedule_timezone"] = instance.schedule_timezone or "Europe/Kyiv"

        if not validated_data.get("backup_directory"):
            validated_data["backup_directory"] = instance.backup_directory or "Backup"

        return super().update(instance, validated_data)


class DatabaseBackupRunSerializer(serializers.Serializer):
    dispatch_async = serializers.BooleanField(required=False, default=True)


class DatabaseBackupSettingsAPIView(BackofficeAPIView):
    def get(self, request):
        backup_settings = get_database_backup_settings()
        return Response(DatabaseBackupSettingsSerializer(backup_settings).data)

    def patch(self, request):
        backup_settings = get_database_backup_settings()
        serializer = DatabaseBackupSettingsUpdateSerializer(backup_settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        backup_settings.refresh_from_db()
        return Response(DatabaseBackupSettingsSerializer(backup_settings).data)


class DatabaseBackupRunAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = DatabaseBackupRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispatch_async = serializer.validated_data.get("dispatch_async", True)

        from apps.core.tasks.database_backup import run_database_backup_task

        if dispatch_async:
            task = run_database_backup_task.delay()
            return Response({"mode": "async", "task_id": task.id}, status=status.HTTP_202_ACCEPTED)

        result = run_database_backup_task()
        return Response({"mode": "sync", "result": result}, status=status.HTTP_200_OK)


def _extract_schedule_time_from_cron(cron_expression: str) -> time:
    parts = str(cron_expression or "").split()
    if len(parts) != 5:
        return time(hour=23, minute=0)

    minute_raw, hour_raw = parts[0], parts[1]
    if not minute_raw.isdigit() or not hour_raw.isdigit():
        return time(hour=23, minute=0)

    minute = int(minute_raw)
    hour = int(hour_raw)
    if minute < 0 or minute > 59 or hour < 0 or hour > 23:
        return time(hour=23, minute=0)

    return time(hour=hour, minute=minute)
