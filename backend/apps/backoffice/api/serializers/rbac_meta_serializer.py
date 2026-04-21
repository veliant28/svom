from __future__ import annotations

from rest_framework import serializers


class BackofficeCapabilityDefinitionSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()


class BackofficeSystemRoleSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    group_name = serializers.CharField()
    capabilities = serializers.ListField(child=serializers.CharField())


class BackofficeRbacMetaSerializer(serializers.Serializer):
    roles = BackofficeSystemRoleSerializer(many=True)
    capabilities = BackofficeCapabilityDefinitionSerializer(many=True)
