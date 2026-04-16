from rest_framework import serializers

from apps.supplier_imports.models import ImportRunQuality


class ImportRunQualitySerializer(serializers.ModelSerializer):
    run_id = serializers.CharField(source="run.id", read_only=True)
    source_code = serializers.CharField(source="source.code", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)
    previous_run_id = serializers.CharField(source="previous_run.id", read_only=True)

    class Meta:
        model = ImportRunQuality
        fields = (
            "id",
            "run_id",
            "source",
            "source_code",
            "source_name",
            "previous_run_id",
            "status",
            "total_rows",
            "matched_rows",
            "auto_matched_rows",
            "manual_matched_rows",
            "ignored_rows",
            "unmatched_rows",
            "conflict_rows",
            "error_rows",
            "match_rate",
            "error_rate",
            "match_rate_delta",
            "error_rate_delta",
            "flags",
            "requires_operator_attention",
            "summary",
            "created_at",
            "updated_at",
        )
