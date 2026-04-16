from rest_framework import serializers

from apps.supplier_imports.models import ImportRowError


class ImportRowErrorSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source.code", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = ImportRowError
        fields = (
            "id",
            "run",
            "artifact",
            "source",
            "source_code",
            "source_name",
            "row_number",
            "external_sku",
            "error_code",
            "message",
            "raw_payload",
            "created_at",
            "updated_at",
        )
