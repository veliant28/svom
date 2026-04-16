from rest_framework import serializers

from apps.supplier_imports.models import ArticleNormalizationRule


class ArticleNormalizationRuleSerializer(serializers.ModelSerializer):
    source_code = serializers.CharField(source="source.code", read_only=True)

    class Meta:
        model = ArticleNormalizationRule
        fields = (
            "id",
            "source",
            "source_code",
            "name",
            "rule_type",
            "pattern",
            "replacement",
            "is_active",
            "priority",
            "notes",
            "created_at",
            "updated_at",
        )
