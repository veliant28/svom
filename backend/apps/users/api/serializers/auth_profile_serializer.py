from __future__ import annotations

import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import User

PHONE_FORMAT_REGEX = re.compile(r"^38\(0\d{2}\)\d{3}-\d{2}-\d{2}$")


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "preferred_language",
        )
        extra_kwargs = {
            "email": {"required": False},
            "username": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
            "phone": {"required": False},
            "preferred_language": {"required": False},
        }

    def validate_phone(self, value: str) -> str:
        normalized_value = value.strip()
        if normalized_value and not PHONE_FORMAT_REGEX.fullmatch(normalized_value):
            raise serializers.ValidationError("Phone must match format 38(0XX)XXX-XX-XX.")
        return normalized_value


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, min_length=8, max_length=8, write_only=True)

    def validate_current_password(self, value: str) -> str:
        user: User = self.context["user"]
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        user: User = self.context["user"]
        validate_password(value, user)
        return value
