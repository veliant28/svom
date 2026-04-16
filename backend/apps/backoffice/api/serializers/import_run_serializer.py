from rest_framework import serializers

from apps.backoffice.api.serializers.import_artifact_brief_serializer import ImportArtifactBriefSerializer
from apps.supplier_imports.models import ImportRun


class ImportRunSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source.code", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)
    artifacts = ImportArtifactBriefSerializer(many=True, read_only=True)

    class Meta:
        model = ImportRun
        fields = (
            "id",
            "source",
            "source_code",
            "source_name",
            "status",
            "trigger",
            "dry_run",
            "started_at",
            "finished_at",
            "processed_rows",
            "parsed_rows",
            "offers_created",
            "offers_updated",
            "offers_skipped",
            "errors_count",
            "repriced_products",
            "reindexed_products",
            "summary",
            "note",
            "artifacts",
            "created_at",
            "updated_at",
        )
