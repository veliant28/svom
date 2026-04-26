from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import User

from .phone_utils import normalize_profile_phone


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "preferred_language",
        )
        extra_kwargs = {
            "email": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
            "middle_name": {"required": False},
            "phone": {"required": False},
            "preferred_language": {"required": False},
        }

    def validate_phone(self, value: str) -> str:
        return normalize_profile_phone(value)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, min_length=8, write_only=True)

    def validate_current_password(self, value: str) -> str:
        user: User = self.context["user"]
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        user: User = self.context["user"]
        validate_password(value, user)
        return value
