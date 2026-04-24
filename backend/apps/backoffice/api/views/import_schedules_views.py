from __future__ import annotations

from datetime import time

from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers import ImportSourceSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_import_schedule_sources_queryset
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services import ScheduledImportService


class ImportScheduleListAPIView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportSourceSerializer
    ordering = ("name",)

    def get_queryset(self):
        ScheduledImportService().close_stale_running_runs()
        queryset = get_import_schedule_sources_queryset()
        query = self.request.query_params.get("q", "").strip()
        source_code = self.request.query_params.get("source", "").strip()
        is_enabled = self.request.query_params.get("is_auto_import_enabled", "").strip().lower()

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(supplier__name__icontains=query))
        if source_code:
            queryset = queryset.filter(code=source_code)
        if is_enabled in {"true", "1", "yes"}:
            queryset = queryset.filter(is_auto_import_enabled=True)
        elif is_enabled in {"false", "0", "no"}:
            queryset = queryset.filter(is_auto_import_enabled=False)

        return queryset


class ImportScheduleUpdateSerializer(serializers.ModelSerializer):
    schedule_start_date = serializers.DateField(required=False, allow_null=True, write_only=True)
    schedule_run_time = serializers.TimeField(
        required=False,
        format="%H:%M",
        input_formats=("%H:%M", "%H:%M:%S"),
        write_only=True,
    )
    schedule_every_day = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = ImportSource
        fields = (
            "is_auto_import_enabled",
            "schedule_cron",
            "schedule_timezone",
            "schedule_start_date",
            "schedule_run_time",
            "schedule_every_day",
            "auto_reprice_after_import",
            "auto_reindex_after_import",
            "is_active",
        )

    def validate(self, attrs):
        if "schedule_every_day" in attrs and attrs.get("schedule_every_day") is False:
            raise serializers.ValidationError(
                {"schedule_every_day": "Only daily (7/7) schedule mode is supported."}
            )
        return attrs

    def update(self, instance, validated_data):
        parser_options = dict(instance.parser_options or {})
        has_schedule_cron = "schedule_cron" in validated_data
        has_schedule_every_day = "schedule_every_day" in validated_data
        has_schedule_run_time = "schedule_run_time" in validated_data
        start_date = validated_data.pop("schedule_start_date", serializers.empty)
        run_time = validated_data.pop("schedule_run_time", serializers.empty)
        validated_data.pop("schedule_every_day", None)

        if has_schedule_cron or has_schedule_every_day or has_schedule_run_time:
            if run_time is serializers.empty:
                run_time = _extract_schedule_time_from_cron(
                    str(validated_data.get("schedule_cron") or instance.schedule_cron)
                )
            validated_data["schedule_cron"] = f"{run_time.minute} {run_time.hour} * * *"

        if start_date is not serializers.empty:
            if start_date is None:
                parser_options.pop("schedule_start_date", None)
            else:
                parser_options["schedule_start_date"] = start_date.isoformat()
            validated_data["parser_options"] = parser_options

        if not validated_data.get("schedule_timezone"):
            validated_data["schedule_timezone"] = instance.schedule_timezone or "Europe/Kyiv"

        return super().update(instance, validated_data)


class ImportScheduleUpdateAPIView(UpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportScheduleUpdateSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_import_schedule_sources_queryset()


class ImportScheduleRunSerializer(serializers.Serializer):
    dispatch_async = serializers.BooleanField(required=False, default=True)


class ImportScheduleRunAPIView(UpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ImportScheduleRunSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_import_schedule_sources_queryset()

    def post(self, request, id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = get_object_or_404(self.get_queryset(), id=id)
        dispatch_async = serializer.validated_data.get("dispatch_async", True)

        from apps.supplier_imports.tasks.run_scheduled_supplier_pipeline import run_scheduled_supplier_pipeline_task

        if dispatch_async:
            task = run_scheduled_supplier_pipeline_task.delay(source_code=source.code)
            return Response(
                {
                    "mode": "async",
                    "source_code": source.code,
                    "task_id": task.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        result = run_scheduled_supplier_pipeline_task(source_code=source.code)
        return Response(
            {
                "mode": "sync",
                "source_code": source.code,
                "result": result,
            },
            status=status.HTTP_200_OK,
        )


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
