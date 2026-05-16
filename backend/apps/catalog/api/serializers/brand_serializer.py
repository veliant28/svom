from rest_framework import serializers


class BrandListSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    logo_url = serializers.CharField(required=False, allow_blank=True, default="")
