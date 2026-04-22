from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.rbac import (
    SYSTEM_ROLE_CODES,
    ensure_system_groups_exist,
    get_backoffice_capabilities_for_user,
    get_user_system_role,
    set_user_system_role,
    sync_user_staff_flag_by_system_role,
)


User = get_user_model()


class BackofficeUserGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class BackofficeUserListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    system_role = serializers.SerializerMethodField()
    has_backoffice_access = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "preferred_language",
            "is_active",
            "full_name",
            "groups",
            "system_role",
            "has_backoffice_access",
        )

    def get_full_name(self, obj: User) -> str:
        return (obj.get_full_name() or "").strip() or obj.email

    def get_groups(self, obj: User):
        values = obj.groups.order_by("name").values("id", "name")
        return BackofficeUserGroupSerializer(values, many=True).data

    def get_system_role(self, obj: User) -> str | None:
        return get_user_system_role(obj)

    def get_has_backoffice_access(self, obj: User) -> bool:
        return "backoffice.access" in get_backoffice_capabilities_for_user(obj)


class BackofficeUserDetailSerializer(BackofficeUserListSerializer):
    capabilities = serializers.SerializerMethodField()

    class Meta(BackofficeUserListSerializer.Meta):
        fields = BackofficeUserListSerializer.Meta.fields + (
            "is_staff",
            "is_superuser",
            "capabilities",
        )

    def get_capabilities(self, obj: User) -> list[str]:
        return sorted(get_backoffice_capabilities_for_user(obj))


class _BackofficeUserWriteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    middle_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    preferred_language = serializers.ChoiceField(required=False, choices=("uk", "ru", "en"))
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(required=False, write_only=True, trim_whitespace=False, min_length=8)
    group_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    system_role = serializers.ChoiceField(required=False, allow_null=True, choices=SYSTEM_ROLE_CODES)

    def validate_email(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        queryset = User.objects.filter(email=normalized)
        instance = getattr(self, "instance", None)
        if instance is not None:
            queryset = queryset.exclude(id=instance.id)
        if queryset.exists():
            raise serializers.ValidationError("User with this email already exists.")
        return normalized

    def validate_group_ids(self, value: list[int]) -> list[int]:
        unique_ids = sorted(set(value))
        existing = set(Group.objects.filter(id__in=unique_ids).values_list("id", flat=True))
        missing = [group_id for group_id in unique_ids if group_id not in existing]
        if missing:
            raise serializers.ValidationError(f"Unknown group ids: {missing}")
        return unique_ids

    def validate_first_name(self, value: str) -> str:
        return str(value or "").strip()

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def _apply_groups_and_role(self, *, user: User, validated_data: dict) -> None:
        ensure_system_groups_exist()

        group_ids = validated_data.pop("group_ids", None)
        system_role = validated_data.pop("system_role", serializers.empty)

        if group_ids is not None:
            groups = list(Group.objects.filter(id__in=group_ids).order_by("id"))
            user.groups.set(groups)

        if system_role is not serializers.empty:
            set_user_system_role(user=user, role_code=system_role)
            return

        if not user.groups.exists():
            set_user_system_role(user=user, role_code="user")
            return

        sync_user_staff_flag_by_system_role(user=user)


class BackofficeUserCreateSerializer(_BackofficeUserWriteSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, trim_whitespace=False, min_length=8)

    def create(self, validated_data: dict) -> User:
        ensure_system_groups_exist()

        role_payload: dict[str, object] = {}
        if "group_ids" in validated_data:
            role_payload["group_ids"] = validated_data.pop("group_ids")
        if "system_role" in validated_data:
            role_payload["system_role"] = validated_data.pop("system_role")

        password = validated_data.pop("password")
        normalized_email = validated_data.get("email", "").strip().lower()
        validated_data["email"] = normalized_email
        if "first_name" in validated_data:
            validated_data["first_name"] = str(validated_data["first_name"]).strip()

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        self._apply_groups_and_role(user=user, validated_data=role_payload)
        return user


class BackofficeUserUpdateSerializer(_BackofficeUserWriteSerializer):
    def update(self, instance: User, validated_data: dict) -> User:
        password = validated_data.pop("password", None)

        for field in (
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "preferred_language",
            "is_active",
        ):
            if field in validated_data:
                value = validated_data[field]
                if field == "email":
                    value = str(value).strip().lower()
                setattr(instance, field, value)

        if password:
            instance.set_password(password)

        instance.save()
        self._apply_groups_and_role(user=instance, validated_data=validated_data)
        return instance
