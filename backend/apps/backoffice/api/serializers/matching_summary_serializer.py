from rest_framework import serializers


class MatchingSummarySerializer(serializers.Serializer):
    unmatched = serializers.IntegerField()
    conflicts = serializers.IntegerField()
    auto_matched = serializers.IntegerField()
    manually_matched = serializers.IntegerField()
    ignored = serializers.IntegerField()
