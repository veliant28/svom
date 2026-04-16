from rest_framework import serializers

from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services import ScheduledImportService


class ImportSourceSerializer(serializers.ModelSerializer):
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    last_run = serializers.SerializerMethodField()
    next_run = serializers.SerializerMethodField()

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
        return ScheduledImportService().get_next_run(source=obj)
