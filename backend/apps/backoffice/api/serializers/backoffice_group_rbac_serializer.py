from __future__ import annotations

from django.contrib.auth.models import Group
from rest_framework import serializers

from apps.users.rbac import (
    BACKOFFICE_CAPABILITY_CODES,
    ensure_system_groups_exist,
    get_group_capability_codes,
    get_system_role_for_group_name,
    is_system_role_group,
    normalize_capability_codes,
    replace_group_capabilities,
)


class BackofficeGroupListSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    capability_codes = serializers.SerializerMethodField()
    is_system_role_group = serializers.SerializerMethodField()
    system_role = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id",
            "name",
            "members_count",
            "capability_codes",
            "is_system_role_group",
            "system_role",
        )

    def get_members_count(self, obj: Group) -> int:
        return int(getattr(obj, "members_count", None) or obj.user_set.count())

    def get_capability_codes(self, obj: Group) -> list[str]:
        return get_group_capability_codes(obj)

    def get_is_system_role_group(self, obj: Group) -> bool:
        return is_system_role_group(obj)

    def get_system_role(self, obj: Group) -> str | None:
        return get_system_role_for_group_name(obj.name)


class BackofficeGroupDetailSerializer(BackofficeGroupListSerializer):
    pass


class BackofficeGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    capability_codes = serializers.ListField(child=serializers.ChoiceField(choices=BACKOFFICE_CAPABILITY_CODES), required=False)

    def validate_name(self, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Group name is required.")
        if Group.objects.filter(name=cleaned).exists():
            raise serializers.ValidationError("Group with this name already exists.")
        return cleaned

    def validate_capability_codes(self, value: list[str]) -> list[str]:
        return normalize_capability_codes(value)

    def create(self, validated_data: dict) -> Group:
        ensure_system_groups_exist()
        capability_codes = validated_data.pop("capability_codes", [])
        group = Group.objects.create(name=validated_data["name"])
        replace_group_capabilities(group=group, capability_codes=capability_codes)
        return group


class BackofficeGroupUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    capability_codes = serializers.ListField(child=serializers.ChoiceField(choices=BACKOFFICE_CAPABILITY_CODES), required=False)

    def validate_name(self, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Group name is required.")

        group: Group = self.context["group"]
        if cleaned != group.name and Group.objects.filter(name=cleaned).exists():
            raise serializers.ValidationError("Group with this name already exists.")
        return cleaned

    def validate_capability_codes(self, value: list[str]) -> list[str]:
        return normalize_capability_codes(value)

    def update(self, instance: Group, validated_data: dict) -> Group:
        if is_system_role_group(instance):
            raise serializers.ValidationError({"detail": "System role group cannot be edited."})

        if "name" in validated_data:
            instance.name = validated_data["name"]
            instance.save(update_fields=("name",))

        if "capability_codes" in validated_data:
            replace_group_capabilities(group=instance, capability_codes=validated_data["capability_codes"])

        return instance
