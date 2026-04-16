from rest_framework import serializers


class BackofficeSummarySerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    totals = serializers.DictField()
    status_buckets = serializers.ListField()
    latest_runs = serializers.ListField()
    quality_summary = serializers.DictField(required=False)
    quality_trend = serializers.ListField(required=False)
    match_rate_by_supplier = serializers.ListField(required=False)
    recent_failed_partial = serializers.ListField(required=False)
    recent_degraded_imports = serializers.ListField(required=False)
    requires_operator_attention = serializers.ListField(required=False)
