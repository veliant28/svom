from rest_framework import serializers


class ImportQualitySummarySerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    totals = serializers.DictField()
    latest_by_supplier = serializers.ListField()
    attention_runs = serializers.ListField()
