from rest_framework import serializers

from apps.supplier_imports.models import ImportArtifact


class ImportArtifactBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportArtifact
        fields = (
            "id",
            "file_name",
            "file_format",
            "file_size",
            "status",
            "parsed_rows",
            "errors_count",
            "created_at",
            "updated_at",
        )
